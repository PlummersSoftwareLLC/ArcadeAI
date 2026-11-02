#!/usr/bin/env python3
"""Root-only read-only live bindings and create-only maintenance job preparation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO / 'Robotron'
RUN = GAME / 'logs/managed-learning-20261015/run-26'
CAPTURE = GAME / 'tools/kl_priority_mixture_proposal/recomputed_ce_capture_proposal'
PROPOSAL = CAPTURE / 'live8_maintenance_proposal/revision4'
REVISION = CAPTURE / 'revision2'
PREP = RUN / 'live8-owned-maintenance-root-preparation-reviewed4-20261017'
OUTPUT = RUN / 'live8-owned-maintenance-reviewed4-20261017'
INSURANCE = Path(sys.argv[1]).resolve(strict=True)
assert INSURANCE.parent == RUN and INSURANCE.name.startswith('live8-insurance-')
sys.dont_write_bytecode = True

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def main():
    controller = load(PROPOSAL / 'run_live8_maintenance.py', 'root_live8_preparation')
    sys.path.insert(0, str(GAME / 'tools'))
    primitives = load(GAME / 'tools/parallel_state_fill_trial.py', 'root_live8_owned_helpers')
    trainer = 'robotron-managed-run-26-d3b365c9-trainer.service'
    fleet = 'robotron-managed-run-26-d3b365c9-fleet.service'
    class Host(primitives.LiveHost):
        def runtime_dropin(self):
            return Path('/run/user') / str(os.getuid()) / 'systemd/user' / (self.trainer_unit + '.d') / '90-recomputed-ce-live8.conf'
    host = Host(trainer, fleet)
    before = host.describe()
    host.adopt_initial(before)
    assert host._dropin_bytes() is None
    host.metric_host.configure_logs(before['bindings']['logs'])
    api = host.capture()
    assert api['client_count'] == 192 and api['training_enabled']
    actual_path = INSURANCE / 'insurance-CPU-verification-v4-window-20261017/cpu-verification.json'
    fresh_CPU_release = json.loads((INSURANCE/'CPU-root-execution/root-result-review-and-release.json').read_text())
    assert fresh_CPU_release['status']=='PASS' and fresh_CPU_release['original_exit']==0
    assert hashlib.sha256(actual_path.read_bytes()).hexdigest()==fresh_CPU_release['numeric_report_sha256']
    actual = json.loads(actual_path.read_text())
    assert actual['status'] == 'PASS' and actual['mode'] == 'insurance'
    assert actual['root_job']['insurance']['trainer']['pid'] == host.known_trainer['pid']
    assert all(api[key] >= actual['clocks'][key] for key in controller.CLOCKS)
    source_lock = json.loads((REVISION / 'manifest-source-review-v2.json').read_text())
    baseline_lock = json.loads((REVISION / 'source-lock.json').read_text())
    sources = []
    for name in controller.NAMES:
        dest = GAME / 'Scripts/dqn' / name
        after = controller.fingerprint(REVISION / name)
        assert after['sha256'] == source_lock['files'][name]['sha256']
        before_pin = controller.fingerprint(dest) if dest.exists() else None
        if name == 'recomputed_ce_capture.py':
            assert before_pin is None
        else:
            assert before_pin['sha256'] == baseline_lock['base'][name]['sha256']
        sources.append(dict(destination=str(dest), before=before_pin, after=after))
    assert controller.fingerprint(GAME / 'Scripts/dqn/loss_kernel.py')['sha256'] == source_lock['loss_kernel_sha256']
    helpers = dict(controller=PROPOSAL/'run_live8_maintenance.py', live_host=GAME/'tools/parallel_state_fill_trial.py',
                   metrics=Path(primitives.metrics.__file__).resolve(), identity=Path(primitives.metrics.identity.__file__).resolve(),
                   protection=Path(primitives.protection.__file__).resolve(), bank_state=PROPOSAL/'bank_state_revision2.py')
    context = actual['root_job']['source_control_context']
    executable_argv = REPO / '.venv-gb300/bin/python'
    successful_cpu = INSURANCE / 'CPU-root-execution'
    library_root = REPO / '.venv-gb300/lib/python3.14t/site-packages'
    python_binding = dict(argv_path=str(executable_argv),link_target=os.readlink(executable_argv),
                          link_identity=controller.identity(executable_argv.lstat()),
                          executable=controller.fingerprint(executable_argv.resolve(strict=True)),
                          pyvenv_cfg=controller.fingerprint(executable_argv.parent.parent/'pyvenv.cfg'),
                          library_context=[controller.fingerprint(library_root/tail) for tail in
                                           ('torch/version.py','torch/__init__.py','numpy/version.py','numpy/__init__.py')],
                          successful_execution=controller.fingerprint(successful_cpu/'execution-precommit.json'),
                          successful_completion=controller.fingerprint(successful_cpu/'original-execution-completion.json'),
                          successful_result=controller.fingerprint(successful_cpu/'root-result-review-and-release.json'))
    destinations = {entry['destination'] for entry in sources}
    static_paths = set(before['bindings']['source_hashes']) - destinations
    static_paths.update(before['bindings']['control_hashes'])
    for paths in before['unit_files'].values():
        static_paths.update(paths)
    for module in list(sys.modules.values()):
        path = getattr(module, '__file__', None)
        if path and Path(path).resolve().is_relative_to(GAME / 'tools'):
            static_paths.add(str(Path(path).resolve()))
    static_paths.update(str(path) for path in [GAME/'models_dqn/managed_save.request.json.completed',
                        REVISION/'manifest-source-review-v2.json', REVISION/'source-lock.json',
                        RUN/'quality384M-managed-incumbent-adoption-root-20261017/root-promotion-and-goal-continuation-receipt.json',
                        RUN/'live8-insurance-CPU-root-execution-reviewed1-20261017/root-result-review-and-release.json'])
    static_paths.discard(str(GAME/'models_dqn/game_settings.json'))
    root_job = dict(settings_lifecycle=dict(initial=controller.fingerprint(GAME/'models_dqn/game_settings.json'),parsed_values=json.loads((GAME/'models_dqn/game_settings.json').read_text()),policy='same_bytes_after_owned_stop_only'),schema=controller.SCHEMA, game_root=str(GAME), model_dir=str(GAME/'models_dqn'),
                    experiment=actual['root_job']['experiment'], trainer_unit=trainer, fleet_unit=fleet,
                    output_directory=str(OUTPUT), capture_directory=str(OUTPUT/'ce-recomputed-capture-original8'),
                    sources=sources, before=before, original_dropin=dict(path=str(host.runtime_dropin()),content_base64=None,mode=None),
                    readiness_timeout_s=600,capture_timeout_s=600,baseline_csv=api['csv'],
                    actor_masks={str(actor['pid']):sorted(os.sched_getaffinity(actor['pid'])) for actor in before['bindings']['actors']},
                    worker_mask=host.metric_host.mask(before['bindings']['worker']),
                    helper_pins={key:controller.fingerprint(value) for key,value in helpers.items()},
                    static_pins=[controller.fingerprint(path) for path in sorted(static_paths)],
                    insurance_verification=controller.fingerprint(INSURANCE/'insurance-CPU-verification-v4-window-20261017/cpu-verification.json'),
                    insurance_receipt=controller.fingerprint(INSURANCE/'saved-insurance-receipt.json'),
                    verifier=dict(script=controller.fingerprint(RUN/'live8-maintenance-checkpoint-CPU-verifier-proposal-20261017/verify_maintenance_checkpoint.py'),
                                  python=str(executable_argv),python_binding=python_binding,timeout_s=120,context=context),
                    bank_spec=dict(ring='/dev/shm/robotron_dqn_latest_replay',model_dir=str(GAME/'models_dqn'),capacity=6000000,
                                   state_size=11128,episode_capacity=192,bank_strides=dict(hof=1536,ephof=2048)))
    assert all(mask == list(range(72)) for mask in root_job['actor_masks'].values())
    assert root_job['worker_mask'] == list(range(72))
    assert len(root_job['actor_masks']) == 192 and not OUTPUT.exists()
    # No production write, save request, source install, actor signal or unit action.
    PREP.mkdir()
    controller.publish(PREP/'fresh-root-api.json',api)
    record = controller.publish(PREP/'root-job.json',root_job)
    controller.publish(PREP/'root-preparer-source-pin.json',controller.fingerprint(Path(__file__).resolve()))
    print(json.dumps(dict(job=record,preparation_only=True,actions=False),indent=2))

if __name__ == '__main__':
    main()
