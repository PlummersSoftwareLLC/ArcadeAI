#!/usr/bin/env python3
"""UNSELECTED coordinated member; default PLAN does not read or import sources.

Reuses the immutable continuous-guard evaluator's actor, fleet, protocol,
timeout-accounting and cleanup primitives. Only the lifecycle is coordinated.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent


def command_contract(value, case_sha, parent, parent_alive):
    if (type(value) is not dict or value.get('case_sha256') != case_sha
            or value.get('parent') != parent or parent_alive is not True):
        raise ValueError('Foreign/dead parent command')
    return value


def padding_contract(status, clocks, frozen_clocks, replay, frozen_replay, boundary_ready):
    if (status.get('complete') is not True or status.get('valid') is not True
            or status.get('cohort', {}).get('complete') is not True
            or clocks != frozen_clocks or replay != frozen_replay or boundary_ready is not True):
        raise ValueError('Original cohort or frozen padding state invalid')
    return True


def execute(args):
    # Authenticate the stdlib parent/common source BEFORE importing it.
    raw = Path(args.manifest).read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.manifest_sha256:
        raise ValueError('Manifest SHA differs')
    declared = json.loads(raw)['files']['joint_parent.py']
    parent_source = HERE / 'joint_parent.py'
    if declared['path'] != str(parent_source) or hashlib.sha256(parent_source.read_bytes()).hexdigest() != declared['sha256']:
        raise ValueError('Parent source differs')
    module_spec = importlib.util.spec_from_file_location('_parallel_quality_parent', parent_source)
    P = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = P
    module_spec.loader.exec_module(P)
    inventory, manifest_pin = P.manifest(args.manifest, args.manifest_sha256)
    case_pin, case_raw = P.pin(args.case)
    P.require(case_pin['sha256'] == args.case_sha256 and case_pin['identity']['mode'] == '0o444', 'Case differs')
    case = P.decoded(case_raw)
    ownership = P.decoded((Path(case['output_directory']) / 'parent-ownership.json').read_bytes())
    plan = P.decoded(P.pinned(ownership['plan']))
    P.require(ownership['case'] == case_pin and plan['case'] == case_pin and plan['source_manifest'] == manifest_pin,
        'Parent/plan/case binding differs')
    parent = ownership['parent']
    P.require(P.alive(parent) and os.getppid() == parent['pid']
        and P.process_cgroup(os.getpid()) == parent['cgroup'], 'Original parent/cgroup required')
    lease_fd = int(os.environ['ROBOTRON_PARALLEL_GPU0_LEASE_FD'])
    P.require(lease_fd == plan['lease']['descriptor'] and P.lease_identity(lease_fd) == plan['lease']['identity']
        and P.lease_identity(lease_fd) == {key: P.identity(P.LEASE.lstat())[key]
            for key in ('device', 'inode', 'mode', 'uid', 'nlink')}, 'Inherited lease identity differs')
    # The same-description lock is already held; this does not unlock it.
    P.fcntl.flock(lease_fd, P.fcntl.LOCK_EX | P.fcntl.LOCK_NB)
    P.require(type(args.member) is int and 1 <= args.member <= 4, 'One explicit member required')
    spec = plan['legs'][args.member - 1]
    P.require(spec['index'] == args.member and spec['job']['port'] == case['ports'][args.member - 1], 'Member namespace differs')
    E = P.load(P.BASE / 'run_frozen_sidecar.py', '_parallel_quality_member_evaluator')
    fields = dict(spec['job'])
    job = E.Job(Path(fields['checkpoint']), Path(fields['directory']), fields['label'], fields['device'],
        fields['gpu_uuid'], fields['port'], fields['cohort_s'], fields['timeout_s'], fields['wait_us'],
        Path(fields['mame']), Path(fields['rompath']), fields['cpu_threads'], Path(fields['boot_assets']),
        fields['inference_backend'], game_boundary_diagnostics=fields['game_boundary_diagnostics'],
        continuous_guard_manifest=Path(fields['continuous_guard_manifest']),
        continuous_guard_manifest_sha256=fields['continuous_guard_manifest_sha256'])
    P.require(job.plan() == fields and P.PROFILE == plan['profile'], 'Exact inherited Job profile required')
    owner = dict(pid=os.getpid(), starttime_ticks=P.process_start(os.getpid()), cgroup=P.process_cgroup(os.getpid()))
    stopped = threading.Event()
    prior_handlers = {number: signal.signal(number, lambda *_: stopped.set()) for number in (signal.SIGTERM, signal.SIGINT)}
    fleet = server = worker = controller = actor = None
    guard_installer = guard_token = guard_initial = None
    guard_pre_serve = guard_after_cleanup = None
    guard_checks, guard_error = 0, None
    metadata, boot_identity, loaded_source_hashes = {}, {}, {}
    checkpoint = identity = library = selected_guard = None
    proof_ready = False
    result, failure, cleanup_errors, actors = {}, None, [], []
    admitted = cohort_done = False
    all_padding_valid = True
    started = time.time()
    control = Path(case['output_directory']) / 'control'

    def message(stage, **value):
        return P.publish(job.directory / (stage + '.json'), dict(
            schema='robotron-parallel-quality-member-message-v1', case_sha256=case_pin['sha256'],
            index=args.member, stage=stage, owner=owner, **value))

    def command(name, *, required=False):
        path = control / (name + '.json')
        if not path.exists():
            P.require(not required, 'Missing parent command')
            return None
        value = P.decoded(path.read_bytes())
        return command_contract(value, case_pin['sha256'], parent, P.alive(parent))

    def wait_command(name, seconds):
        deadline = time.monotonic() + seconds
        while True:
            P.require(not stopped.is_set() and P.alive(parent), 'Interrupted/dead parent before joint stage')
            if value := command(name):
                return value
            P.require(time.monotonic() < deadline, 'Fixed parent coordination budget expired')
            time.sleep(.05)

    def owned_popen(argv, **kwargs):
        # Actual original fleet Popen is retained by E.PrivateFleet. This ledger
        # is evidence only, never authority for wildcard PID cleanup.
        process = subprocess.Popen(argv, **P.with_lease(kwargs, lease_fd))
        try:
            item = dict(pid=process.pid, starttime_ticks=P.process_start(process.pid),
                cgroup=P.process_cgroup(process.pid), slot=int(kwargs['env']['ROBOTRON_CLIENT_SLOT']))
            P.require(item['starttime_ticks'] is not None and item['cgroup'] == parent['cgroup'], 'Actor escaped owned cgroup')
            actors.append(item)
            P.publish(job.directory / f'actor-owned-{item["slot"]}.json', dict(actor=item,
                argv=argv, cwd=str(kwargs['cwd']), port=job.port, case=case_pin,
                inherited_lease_descriptor=lease_fd, lease_identity=P.lease_identity(lease_fd)))
            return process
        except BaseException:
            # The just-created original handle is the only thing signaled here.
            process.terminate()
            process.wait(timeout=5)
            raise

    try:
        job.validate(require_boot_assets=True)
        boot_identity = E.boot_module().load_snapshot(job.boot_assets)
        E.configure_environment(job)
        job.directory.mkdir(parents=True)
        checkpoint, identity = E.copy_checkpoint(job)
        selected_guard = E.guard_selection(job.continuous_guard_manifest, job.continuous_guard_manifest_sha256)
        P.publish(job.directory / 'plan.json', dict(job.plan(), checkpoint_sha256=identity,
            effective_implementation=selected_guard, canonical_source_hashes_are_base_provenance=True))
        sys.path.insert(0, str(E.GAME / 'Scripts'))
        import torch
        from dqn import config
        from dqn.inference_actor import InferenceActor
        from dqn.managed_measurement import ManagedMeasurement
        from dqn import socket_server as socket_module
        P.require(E.guard_selection(job.continuous_guard_manifest, job.continuous_guard_manifest_sha256)
            == selected_guard, 'Guard declaration changed before installation')
        guard_installer, guard_token = E.install_guard(socket_module, selected_guard)
        guard_initial = E.verify_guard(guard_installer, guard_token, selected_guard)
        torch.set_num_threads(job.cpu_threads)
        torch.set_num_interop_threads(1)
        config.RL_CONFIG.inference_batch_max_size = E.ACTORS
        actor = E.build_inference_actor(InferenceActor, checkpoint, job)
        metadata = dict(actor.checkpoint_metadata)
        P.require(metadata.get('total_training_steps', actor.training_steps) == actor.training_steps
            and metadata.get('total_optimized_samples', actor.optimized_samples) == actor.optimized_samples,
            'Checkpoint metric/actor clocks differ')
        for key in ('learner_frame_count', 'frame_count', 'measurement_frame_count'):
            setattr(config.metrics, key, int(metadata[key]))
        config.metrics.total_training_steps = int(metadata.get('total_training_steps', actor.training_steps))
        config.metrics.total_optimized_samples = actor.optimized_samples
        config.metrics.training_enabled = False
        config.metrics.preview_capture_enabled = False
        config.metrics.hud_enabled = False
        for name, value in dict(start_advanced=False, start_level_min=1, epsilon_pct=0,
                expert_pct=0, auto_curriculum=False, difficulty=5).items():
            setattr(config.game_settings, name, value)
        from build_socket_wait import build
        library = build(job.directory / 'socket-wait-build') if job.wait_us else None
        server = socket_module.SocketServer('127.0.0.1', job.port, actor, replay_enabled=False)
        P.require(server.async_buffer is None and actor.checkpoint_sha256 == identity, 'Replay/checkpoint isolation failed')

        def boundary(generation):
            value = E.fixed_boundary(server, generation)
            # The controller's original timeout runs during connection warmup.
            # Only its admission readiness is gated; no clock is rearmed.
            value['ready'] = bool(value['ready'] and command('admit') is not None)
            return value

        controller = ManagedMeasurement(actor, config.metrics, server.game_journal, boundary_status=boundary)
        fleet = E.PrivateFleet(job, library, popen=owned_popen, expected_boot_identity=boot_identity['identity'])
        worker = threading.Thread(target=server.start, name='frozen-sidecar-server', daemon=True)
        checkpoint_signature = E.checkpoint_identity(checkpoint)
        loaded_source_hashes = E.source_hashes()
        P.require(loaded_source_hashes == plan['evaluator_source_hashes'], 'Base evaluator source map differs')
        proof_ready = True
        message('prepared', checkpoint_sha256=identity, numeric_policy=actor.numeric_policy,
            compile_report=actor.compile_report, effective_implementation=guard_initial,
            inherited_lease_descriptor=lease_fd, lease_identity=P.lease_identity(lease_fd),
            GPU_peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
            GPU_peak_reserved_bytes=torch.cuda.max_memory_reserved(0), serving_started=False)
        start = wait_command('start', 1800)
        controller.enter(job.label, cohort_s=job.cohort_s, timeout_s=job.timeout_s)
        guard_pre_serve = E.verify_guard(guard_installer, guard_token, selected_guard)
        P.require(guard_pre_serve == guard_initial, 'Guard changed before serving')
        guard_checks += 1
        worker.start()
        bind_deadline = time.monotonic() + 15
        while not server.running:
            P.require(worker.is_alive() and time.monotonic() < bind_deadline, 'Server did not bind')
            time.sleep(.02)
        fleet.launch()
        connected = False
        while True:
            current_guard = E.verify_guard(guard_installer, guard_token, selected_guard)
            P.require(current_guard == guard_initial, 'Effective guard changed')
            guard_checks += 1
            E.check_protocol(config, actor, checkpoint_signature, checkpoint)
            P.require(P.alive(parent) and P.process_cgroup(os.getpid()) == parent['cgroup'], 'Parent/cgroup changed')
            P.require(not server.inference_only_error and not actor.inference_error, 'Server/inference failure')
            P.require(not fleet.exited() and worker.is_alive() and server.running, 'Owned actor/server exited')
            P.descriptor_retained(os.getpid(), lease_fd, plan['lease']['identity'])
            for item in actors:
                P.require(P.alive(item), 'Actor identity/cgroup changed')
                P.descriptor_retained(item['pid'], lease_fd, plan['lease']['identity'])
            if stop := command('stop'):
                P.require(cohort_done and stop['reason'] == 'all_four_original_cohorts_complete', 'Premature joint stop')
                break
            P.require(not stopped.is_set(), 'Member interrupted without completed joint stop')
            ready = E.fixed_boundary(server, controller.generation)
            if ready['ready'] and not connected:
                message('connected', boundary=ready, actors=list(actors),
                    timeout_entered_unix_s=controller._entered_ts)
                connected = True
            admission = command('admit')
            if admission is not None:
                P.require(time.monotonic() < admission['joint_deadline_monotonic_s'], 'Joint timeout expired')
            status = controller.tick()
            if status['phase'] != 'warming':
                P.require(ready['ready'], 'Actor disconnected/changed after admission')
            if controller.start_ts is not None:
                admitted = True
            if status['complete']:
                P.require(status['valid'] is True and status['cohort']['complete'] is True, 'Original cohort invalid/incomplete')
                if not cohort_done:
                    result = status
                    message('cohort_complete', cohort_start_unix_s=controller.start_ts,
                        cohort_close_unix_s=controller.close_ts, count=status['count'],
                        inference_requests=int(config.metrics.total_inference_requests),
                        inference_wait_total_s=float(config.metrics.total_inference_time))
                    cohort_done = True
                # Preserve four serving populations; no new admission is made.
                padding_contract(status, controller._clock_values(), controller._clocks,
                    controller._replay_values(), controller._replay_guard, ready['ready'])
            if not admitted:
                P.require(time.monotonic() < start['issued_monotonic_s'] + 180, 'Joint readiness/admission exceeded budget')
            time.sleep(.1)
    except BaseException as error:
        failure = f'{type(error).__name__}: {error}'
        all_padding_valid = False
        result = dict(controller.status() if controller is not None else {},
            complete=True, valid=False, reason='parallel_member_failed', error=failure)
    finally:
        timeout_diagnostics = {}
        if all(x is not None for x in (fleet, server, worker, controller)):
            try:
                timeout_diagnostics, cleanup_errors = E.cleanup_with_timeout_evidence(
                    fleet, server, worker, controller, {})
            except BaseException as error:
                cleanup_errors.append(f'Cleanup failed: {type(error).__name__}: {error}')
        if guard_installer is not None:
            try:
                guard_after_cleanup = E.verify_guard(guard_installer, guard_token, selected_guard)
                P.require(guard_after_cleanup == guard_initial, 'Guard changed after cleanup')
                P.require(E.guard_selection(job.continuous_guard_manifest, job.continuous_guard_manifest_sha256)
                    == selected_guard, 'Guard source declaration changed after cleanup')
                guard_checks += 1
            except BaseException as error:
                guard_error = f'{type(error).__name__}: {error}'
        for number, handler in prior_handlers.items():
            signal.signal(number, handler)
    actor_closure_complete = not cleanup_errors and all(not P.alive(item) for item in actors)
    if proof_ready:
        effective_guard = dict(selection=selected_guard, runtime_code_sha256=guard_initial['runtime_code_sha256'],
            python_version=guard_initial['python_version'], python_cache_tag=guard_initial['python_cache_tag'],
            verified_before_serving=guard_pre_serve is not None, verified_after_cleanup=guard_error is None,
            verification_count=guard_checks, verification_error=guard_error,
            local_identity_before=guard_initial['local_identity'],
            local_identity_after=(guard_after_cleanup or {}).get('local_identity'))
        result.update(active=False, phase='finished', job=job.plan(), checkpoint_sha256=identity,
            effective_implementation=effective_guard,
            source_hashes_scope='canonical E13 base; mandatory effective_implementation is additional',
            checkpoint_path=str(checkpoint), source_checkpoint_path=str(job.checkpoint),
            checkpoint_metadata=metadata, numeric_policy=actor.numeric_policy,
            inference_backend=job.inference_backend, compile_report=actor.compile_report,
            boot_assets=boot_identity, boot_restores=fleet.boot_restores if fleet is not None else {},
            **timeout_diagnostics, cleanup_errors=cleanup_errors, ended_unix_s=time.time(), elapsed_s=time.time()-started,
            runtime=dict(torch=torch.__version__, device=job.device, cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],
                cuda=torch.version.cuda, cudnn=torch.backends.cudnn.version(), gpu_name=torch.cuda.get_device_name(0),
                compute_capability=list(torch.cuda.get_device_capability(0))),
            engine_version=metadata['engine_version'], state_size=metadata['state_size'],
            single_frame_state_size=metadata['single_frame_state_size'], frame_stack=metadata['frame_stack'],
            wire_params_count=config.WIRE_PARAMS_COUNT, wire_version=2, frame_protocol='robotron-v2',
            source_hashes=loaded_source_hashes if 'loaded_source_hashes' in locals() else E.source_hashes(),
            ended_source_hashes=E.source_hashes(), socket_wait=dict(wait_us=job.wait_us, port=job.port,
                library=str(library) if library else None, sha256=E.sha256(library) if library else None,
                actors=fleet.backend_evidence() if fleet is not None else {}),
            server_error=server.inference_only_error if server is not None else None,
            inference_error=actor.inference_error)
        reasons = []
        if failure: reasons.append('parallel_member_failure')
        if cleanup_errors or not actor_closure_complete: reasons.append('sidecar_cleanup_failed')
        if guard_error is not None: reasons.append('effective_guard_verification_failed')
        if result['server_error']: reasons.append('server_or_actor_connection_failed')
        if result['inference_error']: reasons.append('actor_inference_failed')
        if any(result.get('actor_timeout_logs', {}).values()): reasons.append('actor_action_receive_timeout')
        if (len(result['socket_wait']['actors']) != E.ACTORS or
                not all(row['matching_activation'] for row in result['socket_wait']['actors'].values())):
            reasons.append('socket_wait_backend_not_verified')
        if result['source_hashes'] != result['ended_source_hashes']: reasons.append('source_changed_during_evaluation')
        if E.sha256(checkpoint) != identity: reasons.append('checkpoint_copy_hash_changed')
        try:
            if E.boot_module().load_snapshot(job.boot_assets)['identity'] != boot_identity['identity']:
                reasons.append('boot_snapshot_changed_during_evaluation')
        except (OSError, ValueError, RuntimeError):
            reasons.append('boot_snapshot_invalid_after_evaluation')
        E.retain_invalidity_reasons(result, reasons)
        if result.get('valid'):
            try:
                from compare_frozen_measurements import validate_receipt
                validate_receipt(result)
                result['receipt_validator'] = 'passed'
            except ValueError as error:
                result.update(valid=False, reason='receipt_validation_failed', validation_error=str(error))
                result['invalidity_reasons'].append('receipt_validation_failed')
    result['parallel_profile'] = dict(profile=P.PROFILE, case=case_pin, manifest=manifest_pin,
        parent=parent, member_owner=owner, full_cohort_scoring_unchanged=True,
        held_through_joint_stop=cohort_done and failure is None,
        unscored_padding_faults_validated=True, actor_closure_complete=actor_closure_complete)
    if job.directory.exists():
        E.write_json(job.directory / 'receipt.json', result)
        message('closed', actors=actors, actor_closure_complete=actor_closure_complete,
            all_padding_valid=bool(all_padding_valid and not failure and not cleanup_errors and guard_error is None
                and result.get('valid') is True), original_member_result=result.get('valid') is True,
            receipt= P.pin(job.directory / 'receipt.json')[0])
    print(json.dumps(dict(index=args.member, valid=result.get('valid', False), error=failure)))
    return 0 if result.get('valid') is True and actor_closure_complete else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--case', type=Path)
    parser.add_argument('--case-sha256')
    parser.add_argument('--member', type=int)
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: parent-owned coordinated member; no source reads/imports/runtime actions')
        return 0
    if not all((args.manifest, args.manifest_sha256, args.case, args.case_sha256, args.member)):
        raise ValueError('Explicit pinned parent case/manifest/member required')
    return execute(args)


if __name__ == '__main__':
    raise SystemExit(main())
