"""Prepare one CPU verification job from the completed, original window.

This prepares metadata and an independent checkpoint copy. It never launches a
verifier, modifies training, repeats capture, evaluates or promotes a policy.
"""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
BASE = GAME/'logs/managed-learning-20261015/run-26'
WINDOW_PREP = BASE/'post-confirmed-scoring-next8M-original01-root-preparation-20261018'
WINDOW_SOURCE_SHA = 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3'
CLOCKS = ('training_steps', 'optimized_samples', 'learner_frame_count', 'frame_count')


def require(value, message):
    if not value:
        raise ValueError(message)


def prepare(destination, expected_window_job_sha256):
    source = GAME/'tools/post_continuity_window.py'
    import hashlib
    require(hashlib.sha256(source.read_bytes()).hexdigest() == WINDOW_SOURCE_SHA,
            'Original window source changed')
    spec = importlib.util.spec_from_file_location('_original_post_continuity_window', source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    pin, publish = module.pin, module.publish
    window_job = WINDOW_PREP/'job.json'
    require(pin(window_job)['sha256'] == expected_window_job_sha256, 'Original window job changed')
    window = json.loads(window_job.read_text()); out = Path(window['output'])
    result_path = out/'result.json'; result = json.loads(result_path.read_text())
    require(result['status'] == 'CAPTURED_FIRST_BOTH_HORIZONS'
            and result['tag'] == window['tag'] and result['owner'] == window['owner'],
            'Only the completed original capture is eligible')
    delta = result['progress']
    require(delta['both_horizons'] is True and delta['learner_frames'] >= 8_000_000
            and delta['learner_accepted'] >= 8_000_000, 'Both original horizons required')
    require(result['CPU_verified'] is result['quality_qualified'] is result['promotion'] is False,
            'Capture receipt must not claim later verification or qualification')
    trigger = Path(result['trigger_API']['path'])
    require(pin(trigger) == result['trigger_API'], 'Original trigger API changed')
    api = json.loads(trigger.read_text())
    require(api['client_count'] == 192 and api['managed_experiment'] == window['experiment'],
            'Actual acquisition scope differs')
    floor = {key: api[key] for key in CLOCKS}
    require(all(type(value) is int and value > 0 for value in floor.values()),
            'Exactly four positive acquisition clocks required')
    checkpoint = result['checkpoint']
    require(pin(checkpoint['path']) == checkpoint and checkpoint['identity']['mode'] == '0o444'
            and checkpoint['identity']['nlink'] == 1, 'Readonly original checkpoint changed')
    require(module.process_start(window['owner']['pid']) == window['owner']['starttime_ticks'],
            'Original owner changed since capture')
    # The managed completed-slot hash is intentionally historical after capture;
    # all other held inputs still have to match their prospective commitments.
    for path, digest in window['held_hashes'].items():
        if path.endswith('/managed_save.request.json.completed'):
            continue
        require(pin(path)['sha256'] == digest, 'Held input changed: '+path)

    destination.mkdir(mode=0o700)
    copied = destination/'candidate-readonly-copy.pt'
    with Path(checkpoint['path']).open('rb') as incoming, copied.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush(); os.fchmod(outgoing.fileno(), 0o444); os.fsync(outgoing.fileno())
    copied_pin = pin(copied)
    require(copied_pin['sha256'] == checkpoint['sha256']
            and copied_pin['bytes'] == checkpoint['bytes']
            and pin(checkpoint['path']) == checkpoint, 'Independent copy failed byte verification')

    template_path = BASE/'continuous-guard-same-LR25-continuation-capture-trial01-20261018/candidate-CPU-job.json'
    job = copy.deepcopy(json.loads(template_path.read_text()))
    job.update(experiment=window['experiment'], source=checkpoint,
               verification_copy=copied_pin, clock_floor=floor,
               output_directory=str(destination/'verification'))
    context = job['source_control_context']
    context['archived_control'] = pin(WINDOW_PREP/'control-after.json')
    unit = subprocess.run(['systemctl', '--user', 'cat', window['owner']['unit']],
                          capture_output=True, check=True).stdout
    context['archived_trainer_unit'] = publish(destination/'actual-trainer-unit.txt', unit)
    context['provenance'] = [pin(path) for path in (
        window_job, result_path, out/'first-durable-both-horizons.json', trigger,
        out/'request-publication.json', GAME/'tools/confirmed_game_boundary_proposal/quality_integration_reviewed4/runtime-source-package.json')]

    phase = job['phase_snapshot']
    phase['owner'] = window['owner']; phase['observed_clients'] = api['client_count']
    phase_path = BASE/'boundary-continuity-forward-recovery-original01-20261018/resume-phase-record.json'
    phase['phase_record'] = pin(phase_path)
    record = json.loads(phase_path.read_text())
    phase['boot_checkpoint'] = record['checkpoint']
    phase['boot_verification'] = pin(BASE/'boundary-continuity-forward-recovery-original01-20261018/newest_stopped/CPU-report-readonly.json')
    phase['expected_phase']['last_resume_record_sha256'] = phase['phase_record']['sha256']
    require(record['action'] == 'resume', 'Actual current startup must be described as resume')
    # These eight numerical sources were unchanged by the socket correction.
    # Recheck their exact original identities and independently archived bytes.
    for pair in phase['sources'].values():
        for entry in pair.values():
            require(pin(entry['path']) == entry, 'Original numerical source/archive changed')
    for entry in context['model_package'].values():
        require(pin(entry['path']) == entry, 'Original model source changed')
    acquisition = dict(schema='robotron-owned-phase-snapshot-acquisition-v1',
        purpose='candidate', experiment=window['experiment'], model_dir=str(GAME/'models_dqn'),
        owner_before=window['owner'], owner_after=window['owner'], client_count=api['client_count'],
        source_checkpoint={key:checkpoint[key] for key in ('path','sha256','bytes')},
        clock_floor=floor, phase_record_sha256=phase['phase_record']['sha256'],
        boot_checkpoint=phase['boot_checkpoint'], tag=result['tag'],
        completed_slot_transition=result['completed_slot_transition'], stopped_absence=None)
    phase['acquisition'] = publish(destination/'acquisition.json', acquisition)
    require(phase['purpose'] == 'candidate', 'Actual candidate role required')
    job_pin = publish(destination/'candidate-CPU-job.json', job)
    verifier = GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'
    require(pin(verifier)['sha256'] == job['verifier_sha256'], 'CPU verifier source changed')
    controller = BASE/'production-boundary-replay-integration-original01-root-preparation-20261018/control_private_replay_integration.py'
    config = dict(unit='robotron-confirmed-scoring-candidate-CPU-original01-20261018.service',
        output=str(destination/'controller-execution'),
        argv=[str(ROOT/'.venv-gb300/bin/python'), '-Xgil=0', '-I', '-B', str(verifier),
              '--execute', '--job', str(destination/'candidate-CPU-job.json'),
              '--expected-job-sha256', job_pin['sha256'],
              '--expected-verifier-sha256', job['verifier_sha256']],
        properties=['CPUQuota=200%', 'MemoryMax=4G', 'RuntimeMaxSec=180',
                    'MemorySwapMax=0', 'TasksMax=128', 'TimeoutStopSec=5'],
        pins=[], observation_s=200)
    # The existing bounded controller uses its own smaller metadata identity.
    ctl_spec=importlib.util.spec_from_file_location('_original_cpu_controller', controller)
    ctl=importlib.util.module_from_spec(ctl_spec); ctl_spec.loader.exec_module(ctl)
    config['pins']=[ctl.pin(path) for path in (verifier, destination/'candidate-CPU-job.json', controller)]
    config_pin=publish(destination/'CPU-controller-config.json', config)
    publish(destination/'preparation.json', dict(status='PREPARED_NOT_EXECUTED',
        checkpoint=checkpoint, copy=copied_pin, cpu_job=job_pin, controller_config=config_pin,
        clock_floor=floor, actual_resume=True, template_used_only_for_unchanged_numerical_sources=True,
        no_optimizer_step=True, quality_qualified=False, promotion=False))
    print(json.dumps(dict(cpu_job=job_pin, controller_config=config_pin), indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--window-job-sha256')
    args=parser.parse_args()
    if not args.execute:
        print('PLAN_ONLY: no reads, copies, launches or training changes'); return 0
    require(args.destination and args.destination.is_absolute() and not args.destination.exists(),
            'New absolute preparation destination required')
    require(isinstance(args.window_job_sha256,str) and len(args.window_job_sha256)==64
            and all(x in '0123456789abcdef' for x in args.window_job_sha256),
            'Exact fresh window job SHA256 required')
    prepare(args.destination,args.window_job_sha256); return 0


if __name__ == '__main__':
    raise SystemExit(main())
