"""Prepare NEW corrected numerical case and run its real pre-body context API."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE / 'candidate-CPU-preparation-original01'
NEW = HERE / 'candidate-CPU-preparation-original02'
VERIFIER = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/lr125_phase_cpu_verifier_proposal_20261023/verify_recipe_phase_snapshot.py')


def pin(path):
    path = path.resolve(); raw = path.read_bytes(); s = path.stat()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                      ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink))


def put(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return pin(path)


def controller_pin(value):
    return dict(value, identity={key: value['identity'][key]
                                for key in ('device', 'inode', 'mode', 'uid', 'nlink')})


def main():
    prior_pin = pin(PREVIOUS / 'prepared-candidate-CPU-revision02-NOT-LAUNCHED.json')
    assert prior_pin['sha256'] == '1bafc89d2454f8f0e3da6b07c8d0d9bcd30c1042ef1d225d1c5508f817a15130'
    prior = json.loads(Path(prior_pin['path']).read_text())
    failure_pin = pin(HERE / 'candidate-CPU-execution-original01/root-original-result-and-owned-release.json')
    failure = json.loads(Path(failure_pin['path']).read_text())
    assert failure['original_exit'] == 1 and failure['lifecycle_complete'] is failure['unit_released'] is True
    error_pin = pin(HERE / 'candidate-CPU-execution-original01/stderr.txt')
    assert 'Archived held-control experiment/recipe differs' in Path(error_pin['path']).read_text()
    old_template = json.loads(Path(prior['unchanged_template_job']['path']).read_text())
    job = json.loads(Path(prior['job']['path']).read_text())
    job['experiment'] = old_template['experiment']
    assert job['experiment'] == 'CE4096-LR125-survival32M-original01-20261023'
    job['output_directory'] = str(HERE / 'candidate-CPU-verification-original02')
    NEW.mkdir(mode=0o700)
    acquisition = json.loads(Path(prior['acquisition']['path']).read_text())
    acquisition['experiment'] = job['experiment']
    acquisition['separate_metric_study_label'] = 'deadline-score32-later-policy-firstSave-original01-20261026'
    acquisition['original_numerical_context_failure_preserved'] = failure_pin
    acquisition['original_numerical_context_error_preserved'] = error_pin
    acquisition['corrected_NEW_case_number'] = 2
    acquisition_pin = put(NEW / 'actual-independent-current-policy-acquisition.json', acquisition)
    job['phase_snapshot']['acquisition'] = acquisition_pin
    job['source_control_context']['provenance'].extend([failure_pin, prior['job']])
    job_pin = put(NEW / 'candidate-CPU-job.json', job)
    # Execute the actual exact verifier's metadata stages, then stop BEFORE
    # check_root_copy/validate_checkpoint. Audit rejects model opens/imports.
    denied = []
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            value = os.fsdecode(args[0])
            if value.endswith('.pt'):
                denied.append(value); raise AssertionError('Forbidden model body open: ' + value)
        if event == 'import' and args[0].split('.')[0] in ('torch', 'numpy', 'dqn'):
            denied.append(args[0]); raise AssertionError('Forbidden numerical import')
    sys.addaudithook(audit)
    assert pin(VERIFIER)['sha256'] == job['verifier_sha256']
    spec = importlib.util.spec_from_file_location('_actual_new_case02_verifier', VERIFIER)
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    historical = verifier.load_base()
    args = SimpleNamespace(job=job_pin['path'], expected_job_sha256=job_pin['sha256'],
                           expected_verifier_sha256=job['verifier_sha256'])
    actual_job, actual_job_pin, actual_verifier_pin, output = verifier.read_job(args, historical)
    base, specialization = verifier.select_recipe_base(actual_job, historical)
    evidence = dict(bound_files={})
    model_dir = base.check_context(actual_job, evidence)
    phase, boot, record = verifier.check_acquisition(actual_job, base, evidence, model_dir)
    assert actual_job == job and actual_job_pin['sha256'] == job_pin['sha256'] and not output.exists()
    assert not denied and not any(name.split('.')[0] in ('torch', 'numpy', 'dqn') for name in sys.modules)
    guard_pin = put(NEW / 'actual-NEW-job-prebody-context-and-phase-PASS.json',
        dict(schema='robotron-actual-new-numerical-job-prebody-context-proof-v1', status='PASS',
             actual_job=job_pin, actual_verifier=actual_verifier_pin, recipe_specialization=specialization,
             actual_full_check_context_called=True, actual_full_check_acquisition_called=True,
             stopped_before_actual_check_root_copy_and_validate_checkpoint=True,
             audit_forbids_any_pt_open_and_torch_numpy_dqn_import=True, forbidden_attempts=denied,
             body_loaded_or_tensor_quality_inferred=False, bound_metadata_files=len(evidence['bound_files']),
             actual_expected_phase=phase['expected_phase'], actual_startup_record=record,
             selected_held_recipe=evidence['held_recipe_context']))
    config = json.loads(Path(prior['controller_config']['path']).read_text())
    config['unit'] = 'robotron-deadline32-later-firstSave-numerical-CPU-original02-20261026.service'
    config['output'] = str(HERE / 'candidate-CPU-execution-original02')
    config['argv'][config['argv'].index('--job') + 1] = job_pin['path']
    config['argv'][config['argv'].index('--expected-job-sha256') + 1] = job_pin['sha256']
    config['pins'] = config['pins'][:3] + list(map(controller_pin, [job_pin, prior['checkpoint'],
        prior['independent_readonly_copy'], acquisition_pin, prior['capture_result'], prior['capture_lifecycle'],
        prior['capture_result'] and job['source_control_context']['provenance'][4],
        prior['capture_result'] and job['source_control_context']['provenance'][7], failure_pin, error_pin, guard_pin]))
    config_pin = put(NEW / 'candidate-CPU-controller-config.json', config)
    prepared = dict(prior, schema='robotron-deadline32-candidate-CPU-original02-prepared-NOT-LAUNCHED-v1',
        job=job_pin, controller_config=config_pin, acquisition=acquisition_pin, actual_prebody_guard=guard_pin,
        original01_failure_preserved=failure_pin, corrected_new_case=2, original01_error_preserved=error_pin,
        source_verifier_unchanged=True, original_training_experiment_label_preserved=True,
        numerical_verification_executed=False, CPU_verification_started=False,
        new_metadata_preparation_source=pin(Path(__file__)))
    print(json.dumps(put(NEW / 'prepared-candidate-CPU-NOT-LAUNCHED.json', prepared)), flush=True)


if __name__ == '__main__':
    main()
