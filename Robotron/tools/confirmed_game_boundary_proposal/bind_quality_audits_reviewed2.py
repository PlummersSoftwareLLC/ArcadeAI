"""Bind four original terminal audits to a live, freshly precommitted campaign.

This prepares immutable metadata only. It never starts, stops or retries a
campaign, audit, service, checkpoint acquisition, GPU context or learner.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
BASE = GAME/'logs/managed-learning-20261015/run-26'
HERE = Path(__file__).resolve().parent
EVAL = HERE/'quality_integration_reviewed4/Robotron'
CAMPAIGN = GAME/'logs/managed-learning-20261015/quality-CE845M-vs-confirmed-scoring-LR25-next8M-trial01-20261018'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def prepare(cpu_preparation, native_owner_path, destination):
    window = load('_confirmed_binding_window', GAME/'tools/post_continuity_window.py')
    audit = load('_confirmed_binding_audit', HERE/'audit_confirmed_completed_leg_reviewed2.py')
    watcher = load('_confirmed_binding_watcher', HERE/'watch_confirmed_quality_audits_reviewed2.py')
    require, pin, publish = window.require, window.pin, window.publish
    require(destination.is_absolute() and not destination.exists(), 'New absolute binding directory required')
    owner = json.loads(native_owner_path.read_bytes())
    require(watcher.original_owner(owner) is False, 'Exact native parent must still be live')
    require(owner['unit'] == 'robotron-quality-confirmed-scoring-vs-CE845-original01-20261018.service',
            'Exact future native quality unit required')
    window_preparation = BASE/'post-confirmed-scoring-next8M-original01-root-preparation-20261018'
    window_job_path = window_preparation/'job.json'
    require(pin(window_job_path)['sha256'] == 'cd6a47e2112dffbe68a6ec7da2224337b8b2543702e54b75f4f9982745a68942',
            'Actual original prospective window required')
    window_job = json.loads(window_job_path.read_bytes())
    window_output = Path(window_job['output'])
    result = json.loads((window_output/'result.json').read_bytes())
    require(result['status'] == 'CAPTURED_FIRST_BOTH_HORIZONS', 'Candidate window has not completed')
    window_release_path = window_preparation/'native-terminal-archive/root-original-result-and-owned-release.json'
    window_release = json.loads(window_release_path.read_bytes())
    require(window_release['original_exit'] == 0 and window_release['lifecycle_complete'] is True,
            'Original prospective observer has not been archived and released')
    # Only the documented one-capture completed-slot transition may differ.
    transitioned = result['completed_slot_transition']['after']['actual_pin']
    require(pin(transitioned['path']) == transitioned, 'Actual captured completed slot changed')
    current = copy.deepcopy(window_job)
    current['held_hashes'][transitioned['path']] = transitioned['sha256']
    window.owner_and_files(current)
    completion = json.loads((cpu_preparation/'CPU-completion.json').read_bytes())
    require(completion['status'] == 'PASS' and completion['actual_candidate'] == result['checkpoint'],
            'Exact newly captured CPU candidate proof required')
    for key in ('CPU_report', 'cpu_job', 'original_controller_release'):
        require(pin(completion[key]['path']) == completion[key], 'CPU completion artifact changed')
    release = json.loads(Path(completion['original_controller_release']['path']).read_bytes())
    require(release['original_exit'] == 0 and release['lifecycle_complete'] is True,
            'Original CPU verifier/controller not cleanly archived')
    plan_path = CAMPAIGN/'plan.json'
    plan_pin = pin(plan_path)
    plan = audit.decode(plan_path.read_bytes())
    state = audit.decode((CAMPAIGN/'status.json').read_bytes())
    require(state['plan_sha256'] == plan_pin['sha256'], 'Native status/plan differ')
    candidate = result['checkpoint']
    reference = pin(window_job['quality_precommit']['reference'])
    require(reference['sha256'] == window_job['quality_precommit']['reference_sha256'],
            'Protected reference changed')
    destination.mkdir(mode=0o700)
    # Immutable independent copies bind completed validations whose original
    # driver outputs intentionally retain their original file modes.
    validation_pins = {}
    for name, stem in [('validation_reference','reference'),
                       ('validation_integrated','integrated-no-fire-up')]:
        source = BASE/('confirmed-game-boundary-real-MAME-'+stem+'-original01-20261018/result.json')
        validation_pins[name] = publish(destination/(name+'.json'), source.read_bytes())
    evidence = dict(phase_cpu_job=completion['cpu_job'], phase_cpu_report=completion['CPU_report'],
        window_job=pin(window_job_path), window_result=pin(window_output/'result.json'),
        window_latch=pin(window_output/'first-durable-both-horizons.json'),
        source_package=pin(EVAL.parent/'runtime-source-package.json'), **validation_pins)
    binding = dict(schema='robotron-confirmed-scoring-original-leg-binding-v1',
        campaign=dict(output_directory=str(CAMPAIGN), plan_sha256=plan_pin['sha256'],
            evaluator_source_hashes=plan['evaluator_source_hashes'],
            execution_source_hashes=plan['execution_source_hashes']),
        candidate=candidate, reference=reference, evidence=evidence)
    binding_path = destination/'binding-job.json'
    binding_pin = publish(binding_path, binding)
    args = argparse.Namespace(binding_job=binding_path, binding_job_sha256=binding_pin['sha256'],
        campaign=CAMPAIGN, plan_sha256=plan_pin['sha256'])
    audit.configure(args)
    audit.validate_future_plan(plan, args, CAMPAIGN)
    controller = GAME/'tools/quality_audit_control_gc_repair_proposal/control_audit_reviewed3.py'
    control = load('_confirmed_binding_control', controller)
    require(pin(controller)['sha256'] == 'b5a50047e1a2981a41732c756bf908c6b9b935c58d1d0503c0df494e6f863aee',
            'Selected bounded original-audit controller changed')
    configs = {}
    for index in range(1,5):
        output = destination/f'leg{index:02d}-audit'
        config = dict(unit=f'robotron-confirmed-scoring-leg{index:02d}-audit-original01-20261018.service',
            output=str(destination/f'leg{index:02d}-controller'),
            argv=['/usr/bin/python3.12','-I','-B',str(HERE/'audit_confirmed_completed_leg_reviewed2.py'),
                '--execute','--game',str(EVAL),'--campaign',str(CAMPAIGN),
                '--plan-sha256',plan_pin['sha256'],'--source-sha256',pin(HERE/'audit_confirmed_completed_leg_reviewed2.py')['sha256'],
                '--binding-job',str(binding_path),'--binding-job-sha256',binding_pin['sha256'],
                '--leg',str(index),'--output',str(output)],
            properties=['CPUQuota=100%','MemoryMax=512M','RuntimeMaxSec=60',
                'MemorySwapMax=0','TasksMax=128','TimeoutStopSec=5'],
            pins=[control.pin(p) for p in (controller,HERE/'audit_confirmed_completed_leg_reviewed2.py',binding_path)],
            observation_s=80)
        configs[str(index)] = publish(destination/f'leg{index:02d}-config.json', config)
    job = dict(schema='robotron-original-confirmed-terminal-audit-observer-v1', owner=owner,
        output=str(destination/'observer'), state_path=str(CAMPAIGN/'status.json'),
        plan=plan_pin, configs=configs, controller=pin(controller),
        pins=[pin(p) for p in (controller,HERE/'audit_confirmed_completed_leg_reviewed2.py',
            HERE/'watch_confirmed_quality_audits_reviewed2.py',binding_path)]+list(configs.values())+list(evidence.values()))
    watcher_path = destination/'watcher-job.json'
    watcher_pin = publish(watcher_path, job)
    publish(destination/'preparation.json', dict(status='PREPARED_NOT_LAUNCHED',
        actual_native_owner=owner, native_plan=plan_pin, binding=binding_pin,
        observer_job=watcher_pin, CPU_completion=pin(cpu_preparation/'CPU-completion.json'),
        original_window_release=pin(window_release_path),
        scope='Original read-only terminal audits only; no campaign restart or quality decision.',
        qualification=False,promotion=False))
    require(watcher.original_owner(owner) is False, 'Original parent changed during binding')
    print(json.dumps(dict(binding=binding_pin, watcher_job=watcher_pin,
                         watcher_source=pin(HERE/'watch_confirmed_quality_audits_reviewed2.py')),indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--cpu-preparation', type=Path)
    parser.add_argument('--native-owner', type=Path)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.execute:
        if not all((args.cpu_preparation,args.native_owner,args.destination)):
            parser.error('Exact completed CPU preparation, live native owner and new destination are required')
        prepare(args.cpu_preparation,args.native_owner,args.destination)
    else:
        print('PLAN_ONLY: no reads, outputs, process queries or actions')
