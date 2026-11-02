"""NEW CPU-verification metadata/copy only. Never imports torch or starts jobs."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat
import time


HERE = Path(__file__).resolve().parent
RUN = HERE.parent
OLD = RUN / 'LR125-after-protected3045-firstSave-original01-preparation-20261025/candidate-CPU-preparation-original01'


def identity(path):
    s = path.stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = path.resolve()
    before = identity(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    assert identity(path) == before
    return dict(path=str(path), sha256=digest.hexdigest(), bytes=before['bytes'], identity=before)


def put(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o444)
    return pin(path)


def main():
    old_job = pin(OLD / 'candidate-CPU-job.json')
    old_config = pin(OLD / 'candidate-CPU-controller-config.json')
    assert old_job['sha256'] == 'c498d0c3b9e59c0d0cb4da00f3101b62bc3f1d9063d808c90906d428d3f21c3f'
    assert old_config['sha256'] == '7317c15eb03635e6d8b72888fe2f5e2cb475136a49cbc10b7fec07331ebb8f16'
    result_pin = pin(HERE / 'output-original01/result.json')
    result = json.loads(Path(result_pin['path']).read_text())
    closure_pin = pin(HERE / 'execution-original01/root-original-result-and-owned-release.json')
    closure = json.loads(Path(closure_pin['path']).read_text())
    assert closure['original_exit'] == 0 and closure['unit_released'] is closure['lifecycle_complete'] is closure['audit_success'] is True
    assert result['status'] == 'CAPTURED_ONE_GENUINELY_LATER_POLICY_AFTER_CLOSED_HEALTH_PREFIX'
    assert result['original_attempt'] == 1 and result['no_retry'] is True and result['CPU_verified'] is False
    selection_pin = pin(Path(result['selection']['path']))
    assert selection_pin == result['selection']
    selection = json.loads(Path(selection_pin['path']).read_text())
    assert selection['future_metric']['horizon_s'] == 3600 and selection['future_metric']['scored_rows_per_leg'] == 32
    binding = pin(Path(selection['main_binding']['path']))
    assert binding == selection['main_binding']
    assert result['owner'] == selection['main']['owner']
    source = result['checkpoint']
    source_path = Path(source['path'])
    assert identity(source_path) == source['identity'] and source['identity']['mode'] == '0o444'
    assert source['identity']['uid'] == os.getuid() and source['identity']['nlink'] == 1
    assert source_path.name == result['tag'] + '.pt' and source_path.parent.name == 'managed-checkpoints'
    # Existing verifier requires saved clock >= job floor. Adding one enforces
    # the NEW selection's strict-greater condition on ALL FOUR clocks.
    floor = {key: value + 1 for key, value in selection['required_all4_saved_clocks_strictly_later_than'].items()}
    assert set(floor) == {'learner_frame_count', 'training_steps', 'optimized_samples', 'frame_count'}
    prep = HERE / 'candidate-CPU-preparation-original01'
    prep.mkdir(mode=0o700)
    independent = prep / 'candidate-independent-readonly.pt'
    digest = hashlib.sha256()
    with source_path.open('rb') as original, independent.open('xb') as copied:
        for block in iter(lambda: original.read(1 << 20), b''):
            copied.write(block); digest.update(block)
        copied.flush(); os.fsync(copied.fileno())
    independent.chmod(0o444)
    assert identity(source_path) == source['identity'] and digest.hexdigest() == source['sha256']
    independent_pin = dict(path=str(independent), sha256=digest.hexdigest(),
                           bytes=independent.stat().st_size, identity=identity(independent))
    assert independent_pin['bytes'] == source['bytes']
    assert independent_pin['identity']['inode'] != source['identity']['inode'] and independent_pin['identity']['nlink'] == 1
    job = json.loads(Path(old_job['path']).read_text())
    job['experiment'] = 'deadline-score32-later-policy-firstSave-original01-20261026'
    job['source'] = deepcopy(source)
    job['verification_copy'] = independent_pin
    job['clock_floor'] = floor
    job['output_directory'] = str(HERE / 'candidate-CPU-verification-original01')
    acquisition = dict(schema='robotron-owned-phase-snapshot-acquisition-v1', purpose='candidate',
        experiment=job['experiment'], model_dir=job['source_control_context']['model_dir'],
        owner_before=result['owner'], owner_after=result['owner'], client_count=192,
        source_checkpoint={key: source[key] for key in ('path', 'sha256', 'bytes')},
        clock_floor=floor, phase_record_sha256=job['phase_snapshot']['phase_record']['sha256'],
        boot_checkpoint=job['phase_snapshot']['boot_checkpoint'], tag=result['tag'],
        completed_slot_transition=result['completed_slot_transition'], stopped_absence=None,
        independent_capture_selection=selection_pin, actual_original_capture_result=result_pin,
        actual_original_capture_owned_closeout=closure_pin, current_main_binding=binding,
        deadline_metric_horizon_s=3600, deadline_metric_fixed_denominator=32,
        all_four_saved_clocks_strictly_later_than=selection['required_all4_saved_clocks_strictly_later_than'],
        old_failed_quality_studies_not_requalified=True)
    acquisition_pin = put(prep / 'actual-independent-current-policy-acquisition.json', acquisition)
    job['phase_snapshot']['acquisition'] = acquisition_pin
    job['source_control_context']['provenance'].extend([selection_pin, result_pin, closure_pin, binding])
    job_pin = put(prep / 'candidate-CPU-job.json', job)
    config = json.loads(Path(old_config['path']).read_text())
    config['unit'] = 'robotron-deadline32-later-firstSave-numerical-CPU-original01-20261026.service'
    config['output'] = str(HERE / 'candidate-CPU-execution-original01')
    config['argv'][config['argv'].index('--job') + 1] = job_pin['path']
    config['argv'][config['argv'].index('--expected-job-sha256') + 1] = job_pin['sha256']
    assert config['properties'] == ['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0',
        'RuntimeMaxSec=180', 'TasksMax=256', 'TimeoutStopSec=5', 'SendSIGKILL=no'] and config['observation_s'] == 240
    # Reuse only the exact unchanged three verifier/recipe/strict sources.
    fixed = config['pins'][:3]
    for value in fixed:
        observed = pin(Path(value['path']))
        assert observed['sha256'] == value['sha256'] and observed['bytes'] == value['bytes']
    config['pins'] = fixed + [job_pin, source, independent_pin, acquisition_pin,
                              selection_pin, result_pin, closure_pin, binding]
    config_pin = put(prep / 'candidate-CPU-controller-config.json', config)
    manifest = dict(schema='robotron-deadline32-candidate-CPU-prepared-NOT-LAUNCHED-v1',
        created_unix_s=time.time(), job=job_pin, controller_config=config_pin,
        capture_result=result_pin, capture_lifecycle=closure_pin, acquisition=acquisition_pin,
        unchanged_template_job=old_job, unchanged_template_config=old_config,
        strict_greater_floors=floor, selection_strict_greater_than=selection['required_all4_saved_clocks_strictly_later_than'],
        checkpoint=source, independent_readonly_copy=independent_pin,
        helper_source=pin(Path(__file__)), CPU_verification_started=False,
        body_loaded_or_torch_imported=False, root_adoption_required_before_launch=True,
        old_protected_model_bodies_opened=False, quality_qualified=False)
    print(json.dumps(put(prep / 'prepared-candidate-CPU-NOT-LAUNCHED.json', manifest)), flush=True)


if __name__ == '__main__':
    main()
