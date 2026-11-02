#!/usr/bin/env python3
"""One root-bound immutable milestone candidate; default is literal PLAN only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import sys
import traceback
import types

BASE_PATH = '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/live8-maintenance-checkpoint-CPU-verifier-proposal-20261017/verify_maintenance_checkpoint.py'
BASE_SHA256 = '7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead'
SCHEMA = 'robotron-managed-candidate-checkpoint-CPU-job-v1'
RESULT_SCHEMA = 'robotron-managed-candidate-checkpoint-CPU-result-v1'
CAPTURE_SCHEMA = 'robotron-owned-candidate-capture-execution-v1'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_base():
    """Authenticate exact stdlib source before evaluating it; never run its main."""
    path = Path(BASE_PATH)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == BASE_SHA256, 'Immutable strict verifier changed')
    module = types.ModuleType('_candidate_immutable_strict_verifier')
    module.__file__ = str(path)
    exec(compile(data, str(path), 'exec'), module.__dict__)
    require(module.fingerprint(path)['sha256'] == BASE_SHA256, 'Strict verifier changed during load')
    return module


def read_job(args, base):
    require(args.job is not None and re.fullmatch(r'[0-9a-f]{64}', args.expected_job_sha256 or '')
            and re.fullmatch(r'[0-9a-f]{64}', args.expected_verifier_sha256 or ''),
            'Explicit job and verifier hashes required')
    source = base.fingerprint(Path(__file__).resolve())
    require(source['sha256'] == args.expected_verifier_sha256, 'Candidate verifier changed')
    path = base.canonical(str(args.job))
    require(path.stat().st_size <= base.MAX_JOB, 'Root job exceeds1MiB')
    record = base.fingerprint(path)
    require(record['sha256'] == args.expected_job_sha256, 'Root job hash differs')
    job = json.loads(path.read_text())
    require(base.fingerprint(path) == record, 'Root job changed during parse')
    fields = {'schema', 'verifier_sha256', 'base_verifier_sha256', 'experiment', 'source',
              'verification_copy', 'source_control_context', 'output_directory', 'candidate'}
    require(isinstance(job, dict) and set(job) == fields and job['schema'] == SCHEMA
            and job['verifier_sha256'] == source['sha256']
            and job['base_verifier_sha256'] == BASE_SHA256, 'Candidate root-job schema/source differs')
    require(isinstance(job['experiment'], str) and re.fullmatch(r'[A-Za-z0-9_-]{1,120}', job['experiment']),
            'Invalid experiment')
    output = base.canonical(job['output_directory'], exists=False)
    require(not output.exists() and output.parent.is_dir() and output.parent.stat().st_uid == os.getuid(),
            'Output must be NEW under an owned parent')
    return job, record, source, output


def validate_candidate(job, base, evidence, model_dir):
    """Use the authentic gate four-clock floor; no invented insurance or stopped case."""
    candidate = job['candidate']
    require(isinstance(candidate, dict) and set(candidate) ==
            {'tag', 'target_learner_frames', 'gate', 'completed_request', 'capture_execution'},
            'Candidate binding differs')
    tag, target = candidate['tag'], candidate['target_learner_frames']
    require(isinstance(tag, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', tag), 'Invalid candidate tag')
    base.integer(target, 'target_learner_frames', 1)
    expected_source = str(model_dir / 'managed-checkpoints' / (tag + '.pt'))
    require(job['source']['path'] == expected_source, 'Only the immutable tagged candidate is eligible')
    gate = base.pinned_json(candidate['gate'], evidence, 'candidate_gate')
    require(isinstance(gate, dict) and set(gate) ==
            {'tag', 'target', 'experiment', 'checkpoint', 'trigger_snapshot', 'saved_utc'},
            'Actual completed gate schema differs; no COMPLETE/status field is required')
    require(gate['tag'] == tag and gate['target'] == target and gate['experiment'] == job['experiment']
            and gate['checkpoint'] == expected_source, 'Gate target/tag/branch/checkpoint differs')
    require(isinstance(gate['saved_utc'], str)
            and base.datetime.fromisoformat(gate['saved_utc']).tzinfo is not None, 'Invalid saved timestamp')
    trigger = gate['trigger_snapshot']
    require(isinstance(trigger, dict) and set(trigger) == {*base.CLOCKS, 'client_count'},
            'Gate must carry the original four clocks plus client count')
    for key in base.CLOCKS:
        base.integer(trigger[key], 'trigger.' + key, 1)
    require(type(trigger['client_count']) is int and trigger['client_count'] == 192
            and trigger['learner_frame_count'] >= target, 'Gate triggered early or without192 clients')
    require(candidate['completed_request']['path'] == str(model_dir / 'managed_save.request.json.completed'),
            'Bind the actual completed-request slot before another save reuses it')
    completed = base.pinned_json(candidate['completed_request'], evidence, 'candidate_completed_request')
    require(completed == {'tag': tag}, 'Completed-request tag differs')
    owner = base.pinned_json(candidate['capture_execution'], evidence, 'candidate_capture_execution')
    owner_fields = {'schema', 'trainer_before', 'trainer_after', 'experiment', 'model_dir', 'tag',
                    'target_learner_frames', 'gate_path', 'gate_sha256', 'checkpoint_path',
                    'checkpoint_sha256', 'checkpoint_bytes', 'gate_unit', 'original_exec_code',
                    'original_exit', 'original_result', 'original_terminal_archived_before_release',
                    'terminal_archive'}
    require(isinstance(owner, dict) and set(owner) == owner_fields and owner['schema'] == CAPTURE_SCHEMA,
            'Explicit root-owned capture execution evidence required')
    trainer = base.trainer_identity(owner['trainer_before'])
    require(owner['trainer_after'] == trainer, 'Capture trainer changed; no unknown owner adoption')
    require(owner['experiment'] == job['experiment'] and owner['model_dir'] == str(model_dir)
            and owner['tag'] == tag and owner['target_learner_frames'] == target
            and owner['gate_path'] == candidate['gate']['path']
            and owner['gate_sha256'] == candidate['gate']['sha256']
            and owner['checkpoint_path'] == expected_source
            and owner['checkpoint_sha256'] == job['source']['sha256']
            and owner['checkpoint_bytes'] == job['source']['bytes'], 'Owned capture/source bindings differ')
    unit = owner['gate_unit']
    require(isinstance(unit, dict) and set(unit) == {'pid', 'starttime_ticks', 'unit', 'invocation_id', 'cgroup'},
            'Exact original gate unit identity required')
    base.integer(unit['pid'], 'gate.pid', 1); base.integer(unit['starttime_ticks'], 'gate.starttime_ticks', 1)
    require(isinstance(unit['unit'], str) and re.fullmatch(r'robotron-checkpoint-[A-Za-z0-9_.-]+\.service', unit['unit'])
            and re.fullmatch(r'[0-9a-f]{32}', unit['invocation_id'] or '')
            and isinstance(unit['cgroup'], str) and unit['cgroup'].startswith('/user.slice/')
            and unit['cgroup'].endswith('/' + unit['unit']) and '..' not in unit['cgroup'].split('/'),
            'Invalid original gate service/invocation/cgroup')
    require(type(owner['original_exec_code']) is int and owner['original_exec_code'] == 1
            and type(owner['original_exit']) is int and owner['original_exit'] == 0
            and owner['original_result'] == 'success'
            and owner['original_terminal_archived_before_release'] is True,
            'Original owned helper must have exited0 with terminal evidence archived')
    base.check_pin(owner['terminal_archive'], evidence, 'candidate_original_terminal_archive', metadata=True)
    floor = {key: trigger[key] for key in base.CLOCKS}
    evidence.update(candidate_gate=gate, candidate_capture_execution=owner, clock_floor=floor,
                    capture_owner_scope='Root-pinned historical owner/terminal evidence; no live PID/unit query by verifier')
    return floor


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--job', type=Path)
    parser.add_argument('--expected-job-sha256')
    parser.add_argument('--expected-verifier-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print('PLAN_ONLY: explicit immutable candidate job required; no input reads, numerical imports or outputs')
        return 0
    base = evidence = output = None
    try:
        require(os.environ.get('CUDA_VISIBLE_DEVICES') == '' and 'LD_PRELOAD' not in os.environ
                and 'PYTHONPATH' not in os.environ, 'Start CUDAhidden with preload/PYTHONPATH unset')
        require(not any(name == 'torch' or name.startswith('torch.') or name == 'numpy'
                        or name.startswith('dqn') for name in sys.modules), 'Fresh stdlib-only interpreter required')
        base = load_base()
        job, job_pin, self_pin, output = read_job(args, base)
        base.DIRECTORY = output
        output.mkdir(mode=0o700, exist_ok=False)
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (32 << 20, 32 << 20))
        evidence = dict(schema=RESULT_SCHEMA, status='RUNNING', utc=base.now(), root_job=job,
                        job_file=job_pin, script=self_pin,
                        scope='Immutable tagged checkpoint CPU finite/strict geometry/Adam/scaler/saved-clock verification only')
        base_pin = base.fingerprint(BASE_PATH)
        require(base_pin['sha256'] == BASE_SHA256, 'Strict numerical source changed')
        evidence['base_verifier'] = base_pin
        model_dir = base.check_context(job, evidence)
        floor = validate_candidate(job, base, evidence, model_dir)
        copied = base.check_root_copy(job, evidence)
        base.validate_checkpoint(copied, floor, evidence)
        # The unchanged body checks every saved clock against the authentic gate
        # floor, including learner>=gate trigger>=the explicitly selected target.
        for label, before in evidence['bound_files'].items():
            require(base.fingerprint(before['path']) == before, 'Bound file changed after verification: ' + label)
        require(base.fingerprint(BASE_PATH) == base_pin and base.fingerprint(args.job) == job_pin
                and base.fingerprint(Path(__file__).resolve()) == self_pin, 'Verifier/job identity changed')
        evidence.update(status='PASS', finished_utc=base.now(), path=str(copied),
                        sha256=job['verification_copy']['sha256'], bytes=job['verification_copy']['bytes'],
                        mode_bits='0o444', actual_restore_or_optimizer_step=False,
                        actual_quality_qualification=False)
        base.publish(output / 'cpu-verification.json', evidence)
        print(json.dumps(dict(status='PASS', tag=job['candidate']['tag'], sha256=evidence['sha256'],
                             clocks=evidence['clocks']), indent=2))
        return 0
    except BaseException as error:
        if evidence is not None:
            evidence.update(status='FAIL', finished_utc=base.now(), error=repr(error), traceback=traceback.format_exc())
            try:
                base.publish(output / 'verification-error.json', evidence)
            except BaseException as secondary:
                print('Failure receipt could not persist: ' + repr(secondary), file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
