"""Independent SMALL numerical metadata and exact Tasks256 owned-closeout audit.

Never opens any .pt body, imports torch, retries a job, or changes training.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PREP = HERE / 'candidate-CPU-preparation-original02'
EXEC = HERE / 'candidate-CPU-execution-original02'
REVIEW = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/eval_capacity_proposal/review_original_pilot_score_carry_v1.py')


def identity(path):
    s = path.stat()
    return dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)


def pin(path):
    path = path.resolve()
    assert path.suffix != '.pt', 'No tensor-body reads in independent SMALL review'
    before = identity(path); raw = path.read_bytes(); assert identity(path) == before
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=before)


def read(value, as_json=True):
    actual = pin(Path(value['path']))
    assert all(actual[key] == value[key] for key in ('path', 'sha256', 'bytes'))
    expected = value.get('identity', {key: value[key] for key in actual['identity'] if key in value})
    assert all(actual['identity'][key] == item for key, item in expected.items())
    raw = Path(value['path']).read_bytes()
    return json.loads(raw) if as_json else raw


def main():
    # Make the no-body/no-numerical-import claim process-wide and fail closed.
    forbidden = []
    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)) and os.fsdecode(args[0]).endswith('.pt'):
            forbidden.append(os.fsdecode(args[0])); raise AssertionError('Forbidden model-body open')
        if event == 'import' and args[0].split('.')[0] in ('torch', 'numpy', 'dqn'):
            forbidden.append(args[0]); raise AssertionError('Forbidden numerical import')
    sys.addaudithook(audit)
    manifest_pin = pin(PREP / 'prepared-candidate-CPU-NOT-LAUNCHED.json')
    assert manifest_pin['sha256'] == '8d509e484cd8c65918dae89be4b4dbbdf9a9cfaf2272919eabff34ac47f2b8cf'
    prepared = read(manifest_pin); config = read(prepared['controller_config']); job = read(prepared['job'])
    closure_pin = pin(EXEC / 'root-original-result-and-owned-release.json')
    assert closure_pin['sha256'] == 'c5d590c704e3f591f6f93e813970827a6d81747dfae41f7ba34691e951e08cd0'
    closure = read(closure_pin); owner_pin = pin(EXEC / 'root-original-identity.json'); owner = read(owner_pin)
    review_pin = pin(REVIEW)
    assert review_pin['sha256'] == '8efdb031e52b63e9679b5c1225787019ff86be1d99bf401535d8df53d22d1d9d'
    spec = importlib.util.spec_from_file_location('_exact_archived_closure', REVIEW)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    fields = helper.archived_closure(closure, owner, read, exit_zero=True)
    assert closure['audit_success'] is True and closure['original_exit'] == 0
    properties = dict(value.split('=', 1) for value in config['properties'])
    assert properties == dict(CPUQuota='200%', MemoryMax='4G', MemorySwapMax='0',
        RuntimeMaxSec='180', TasksMax='256', TimeoutStopSec='5', SendSIGKILL='no')
    expected_resources = dict(CPUQuotaPerSecUSec='2s', MemoryMax=str(4 << 30), MemorySwapMax='0',
        RuntimeMaxUSec='3min', TasksMax='256', TimeoutStopUSec='5s', SendSIGKILL='no', Restart='no')
    assert all(fields[key] == value for key, value in expected_resources.items())
    expected_exec = '/usr/bin/env -u LD_PRELOAD -u PYTHONPATH CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 TMPDIR=' + str(EXEC / 'tmp') + ' ' + ' '.join(config['argv'])
    assert expected_exec + ' ; ignore_errors=no ;' in fields['ExecStart']
    for value in config['pins']:
        if Path(value['path']).suffix == '.pt':
            observed = identity(Path(value['path']))
            assert observed['bytes'] == value['bytes']
            assert all(observed[key] == item for key, item in value['identity'].items())
        else:
            read(value, False)
    report_pin = pin(Path(job['output_directory']) / 'cpu-verification.json')
    assert report_pin['sha256'] == 'a0d9efad485ff5718f2f2d15a31cae8a043e1382e722c9970d7961f72b802772'
    report = read(report_pin)
    assert report['status'] == 'PASS' and report['root_job'] == job
    assert report['job_file']['sha256'] == prepared['job']['sha256']
    assert report['script']['sha256'] == job['verifier_sha256'] == '08c165ed917b8633ab658a8efbc915f81e37adff21c1330cd5806cd3148f4051'
    assert report['sha256'] == job['source']['sha256'] == job['verification_copy']['sha256']
    assert report['bytes'] == job['source']['bytes'] == job['verification_copy']['bytes']
    selection = read(report['phase_acquisition']['independent_capture_selection'])
    selected_floor = selection['required_all4_saved_clocks_strictly_later_than']
    clocks = {key: report['clocks'][key] for key in selected_floor}
    assert all(type(value) is int and value > selected_floor[key] and value >= job['clock_floor'][key]
               for key, value in clocks.items())
    assert report['finite'] == dict(tensors=443, scalars=10, integer_scalars=121, tensor_elements=68760333)
    assert report['models'] == {key: dict(strict_cpu_load=True, tensor_count=100, parameter_count=17837490)
                               for key in ('online_state_dict', 'target_state_dict')}
    assert report['adam_state_count'] == 81 and report['adam_group_count'] == 1
    assert len(report['adam_steps']) == 81 and len(report['adam_uninitialized_parameter_names']) == 18
    assert len(set(report['adam_steps']) | set(report['adam_uninitialized_parameter_names'])) == 99
    assert report['adam_step_min'] == report['adam_step_max'] == min(report['adam_steps'].values()) == max(report['adam_steps'].values())
    assert report['logical_training_steps_minus_adam_step'] == clocks['training_steps'] - int(report['adam_step_min'])
    assert report['adam_group']['lr'] == 6.25e-6 and report['adam_group']['eps'] == .00015 and report['adam_group']['fused'] is True
    assert report['held_recipe_context'] == job['source_control_context']['held_recipe_context']
    assert report['phase_metadata_verified'] is True and report['saved_priority_metric_phase']['valid'] is True
    scaler = report['grad_scaler']
    assert all(math.isfinite(value) for value in scaler.values()) and scaler['scale'] > 0
    assert scaler['growth_interval'] == 2000 and 0 <= scaler['_growth_tracker'] < 2000
    assert report['cuda_initialized'] is False and report['visible_cuda_devices'] == 0
    assert report['runtime']['CUDA_VISIBLE_DEVICES'] == '' and report['runtime']['torch_threads'] == report['runtime']['interop_threads'] == 2
    assert not report['actual_restore_or_optimizer_step'] and not report['actual_quality_qualification']
    for key, value in report['bound_files'].items():
        if Path(value['path']).suffix == '.pt':
            current = identity(Path(value['path']))
            assert all(current[name] == value[name] for name in current)
            assert value['sha256'] == report['sha256']
        else:
            read(value, False)
    for name, value in report['private_model_source'].items():
        read(value, False)
        assert Path(value['path']).parent == Path(job['output_directory']) / 'private-source'
        assert value['sha256'] == job['source_control_context']['model_package'][name]['sha256']
    absence = []
    for unit in (owner['unit'], owner['timer']):
        process = subprocess.run(['systemctl', '--user', 'show', unit], capture_output=True, text=True, timeout=5)
        actual = dict(line.split('=', 1) for line in process.stdout.splitlines() if '=' in line)
        assert process.returncode == 0 and actual['Id'] == unit and actual['LoadState'] == 'not-found'
        absence.append(dict(unit=unit, load_state=actual['LoadState'], main_pid=actual.get('MainPID')))
    proc = Path('/proc', str(owner['pid']), 'stat')
    assert not proc.exists() or int(proc.read_text().rsplit(')', 1)[1].split()[19]) != owner['starttime_ticks']
    first_show_pin = pin(EXEC / 'original-first-observed-show-command.json')
    first_show = read(first_show_pin)
    assert first_show['argv'] == ['systemctl', '--user', 'show', owner['unit']] and first_show['exit'] == 0
    first_fields = dict(line.split('=', 1) for line in read(first_show['stdout'], False).decode().splitlines() if '=' in line)
    assert first_fields['InvocationID'] == owner['invocation_id'] and first_fields['MainPID'] == str(owner['pid'])
    assert first_fields['ControlGroup'].endswith('/' + owner['unit'])
    cgroup = Path('/sys/fs/cgroup' + first_fields['ControlGroup']) / 'cgroup.procs'
    assert not cgroup.exists() or not cgroup.read_text().strip()
    assert not forbidden
    result = dict(schema='robotron-deadline32-independent-original02-numerical-small-review-v1',
        status='PASS', root_tool_session_id=2361, original_observed_tool_exit=0,
        prepared=manifest_pin, original_report=report_pin, actual_closure=closure_pin, actual_owner=owner_pin,
        archived_closure_helper=review_pin, source=job['source'], verification_copy=job['verification_copy'],
        saved_clocks=clocks, all_four_strictly_later_than_selection=True,
        finite_tensors=443, model_parameter_count_each=17837490, Adam_slots=81, model_parameters=99,
        saved_Adam_step=report['adam_step_min'], logical_training_steps_minus_Adam_step=report['logical_training_steps_minus_adam_step'],
        Adam_clock_gap_not_attributed_to_one_cause=True, saved_scaler=scaler,
        actual_resources=expected_resources, exact_argv_and_all_six_descriptors_verified=True,
        all_small_source_metadata_hashes_and_all_bound_file_identities_verified=True,
        actual_owned_release_and_current_absence=absence, original_live_cgroup_descriptor=first_show_pin,
        original_owned_cgroup_absent_or_empty=True, model_body_reopened_or_reloaded=False,
        CUDA_initialized_by_original_CPU=False, future_deadline_candidate_only=True,
        improvement_qualified=False, quality_qualified=False, promoted=False,
        review_source=pin(Path(__file__)))
    out = HERE / 'independent-original02-numerical-SMALL-review.json'
    with out.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    out.chmod(0o444)
    print(json.dumps(pin(out)), flush=True)


if __name__ == '__main__':
    main()
