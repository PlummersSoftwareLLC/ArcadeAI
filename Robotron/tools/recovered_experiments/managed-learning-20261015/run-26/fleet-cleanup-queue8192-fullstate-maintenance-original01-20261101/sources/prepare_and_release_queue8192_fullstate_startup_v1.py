"""Default-inert Root metadata constructor and one-use held-trainer release.

No action occurs without one of the explicit modes. No source install, save,
measurement, API request, actor launch, stop, restart or model load is offered.
The release is a permission to begin learning only after exact held restoration.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess

BRIDGE = '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-cold-resume-startup-cap-witness-source-only-original01-20261029/continuous_startup_bridge_cap_witness_v3.py'
BRIDGE_SHA = '47efc654e1a46f281a094b43a8e55802b5f76cbdb62e830b5769a2f6d6e790f4'
INSTALLED_SHA={'/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/agent.py': 'd2a95ff0828df2a00ac86049965b6df304d26b50263b76d027d27a586ff77152',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/bounded_fifo_cleanup_ack_v1.py': 'aab678c023598c90aa0374473eab7da8db9e71818a5d668aee2c222730d92fd8',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/config.py': 'ef26db6aa19fe67ec9e1e15f8227b4e24bbc853b05d0ea00c450b290bf80b249',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/connection_cleanup_receipts.py': 'f27e38411238fcf62256e6b317836b757d31d5e0ac962ec8523dd380236d80ee',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/continuous_startup_bridge.py': '47efc654e1a46f281a094b43a8e55802b5f76cbdb62e830b5769a2f6d6e790f4',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/game_journal.py': '6aa78cb40434793853d17a1032cc6454ac86b0168828848d9d390336ba8678f0',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/main.py': '78178c39b281c0baf52222387f06db2d899c1bf2adfbe8c9fe2fd22729ff59c5',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/managed_driver.py': 'a7ec6dffba18e37b814842d498c8a34ba44f93dce4968ab769d480e329a643ec',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/managed_measurement.py': '39764cfa84572fe36c57e37a5c958d7caa001854c141ebcc161cc973f7b5f3c0',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/metrics_dashboard.py': '9b133ae93eb199ab6b9dc834d7e3879c4f4de2d42dcf07eda1e51b88a8ba2403',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/replay_buffer.py': '34b05e3c4403bc2dca53222222416db2afb733c480ee6238a0cc4e723885d0e8',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/socket_server.py': '6a40b804ee6c1cbad41e84d48cc405fa77b555d46d7188372b2d49e4e1d50c17',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/dqn/training.py': '8cd1e1399c8313c4b9b0465142a72273ffcbb0e1a9053c4c3c9590493f110fe0',
 '/home/dave/source/repos/ArcadeAI/Robotron/Scripts/main.lua': 'bc7df0d6ca18da11cd6498867a5b77e3638d8b721094264f056fe6a949d75f76'}
MODE = 'CONTINUOUS_TRAIN155_EVAL37_ONCE'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def full_pin(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path and not path.is_symlink(),
            'Canonical regular file required')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_nlink == 1
            and 0 < info.st_size <= 4 << 20, 'Bounded owner single-link metadata/source required')
    raw = path.read_bytes()
    identity = lambda s: dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size,
        mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns, mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid, nlink=s.st_nlink)
    require(identity(info) == identity(path.lstat()), 'Selected metadata changed')
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), identity=identity(info))


def source(args):
    actual = full_pin(Path(__file__).resolve())
    require(actual['sha256'] == args.expected_source_sha256 and actual['identity']['mode'] == '0o444',
            'Exact immutable Root operator source required')
    return actual


def bridge_module():
    value = full_pin(BRIDGE)
    require(value['sha256'] == BRIDGE_SHA and value['identity']['mode'] == '0o444', 'Exact frozen bridge source required')
    code = Path(BRIDGE).read_bytes()
    spec = importlib.util.spec_from_file_location('_selected_continuous_startup_bridge', BRIDGE)
    module = importlib.util.module_from_spec(spec)
    exec(compile(code, BRIDGE, 'exec'), module.__dict__)
    return module


def selected_json(path, sha, bridge):
    value = full_pin(Path(path))
    require(value['sha256'] == sha, 'Exact selected metadata SHA required')
    return value, bridge.read(value)


def validate_sources(values, bridge):
    require(type(values) is list and len(values) == len(INSTALLED_SHA), 'Exact fourteen installed source pins required')
    require(len({x['path'] for x in values}) == len(values), 'Duplicate installed source pin')
    require({x['path']: x['sha256'] for x in values} == INSTALLED_SHA, 'Installed source path/bytes differ from selected family')
    for value in values:
        bridge.checked_bytes(value, immutable=False)


def validate_stopped(selection, bridge):
    manifest = bridge.read(selection['restoration_manifest'])
    report = bridge.read(selection['stopped_CPU_report'])
    authority = bridge.read(selection['stopped_state_authority'])
    require(manifest['schema'] == 'robotron-stopped-full-training-state-restoration-manifest-v1'
            and manifest['status'] == 'VERIFIED_STOPPED_STATE' and report['status'] == 'PASS'
            and report['restoration_manifest'] == selection['restoration_manifest']
            and report['original_job'] == manifest['original_job'], 'Stopped CPU/manifest exact join required')
    require(authority['schema'] == 'robotron-root-closed-stopped-full-state-startup-authority-v1'
            and authority['CPU_report'] == selection['stopped_CPU_report']
            and authority['restoration_manifest'] == selection['restoration_manifest']
            and authority['original_CPU_exit'] == 0 and authority['all_original_CPU_resources_closed'] is True
            and authority['old_trainer_and_population_closed'] is True, 'Actual stopped CPU/population closure authority required')
    require(selection['checkpoint'] == manifest['checkpoint'], 'Use the exact unchanged canonical stopped checkpoint')
    # Stream hash only in the explicit Root operation; no torch/model loading.
    checkpoint = Path(selection['checkpoint']['path'])
    require(checkpoint.resolve(strict=True) == checkpoint and not checkpoint.is_symlink(), 'Canonical checkpoint required')
    with os.fdopen(os.open(checkpoint, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = bridge.identity(os.fstat(stream.fileno()))
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode) and before == selection['checkpoint']['identity']
                and before['uid'] == os.getuid() and before['nlink'] == 1, 'Original stopped checkpoint identity differs')
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(sha == selection['checkpoint']['sha256'] and before == bridge.identity(os.fstat(stream.fileno()))
                == bridge.identity(checkpoint.lstat()), 'Original stopped checkpoint changed')
    resume = bridge.read(selection['resume_record'])
    phase = manifest['priority_metric_phase']
    require(resume['schema'] == 'robotron-priority-metric-start-v1' and resume['action'] == 'resume'
            and resume['metric'] == resume['previous_metric'] == 'ce' and resume['phase_id'] == phase['phase_id']
            and resume['root_precommit_sha256'] == phase['root_precommit_sha256']
            and resume['checkpoint'] == {k: selection['checkpoint'][k] for k in ('path','sha256','bytes')}
            and resume['model_dir'] == str(Path(selection['checkpoint']['path']).parent),
            'New resume record must preserve CE founder and exact stopped checkpoint')
    validate_sources(selection['source_pins'], bridge)
    return manifest


def prepare_job(args):
    own = source(args); bridge = bridge_module()
    selected, value = selected_json(args.selection, args.selection_sha256, bridge)
    require(value['schema'] == 'robotron-root-continuous-startup-hold-selection-v1'
            and value['unit'] == 'robotron-trainer.service', 'Exact permanent trainer with future new incarnation required')
    require(type(value['expected_startup_cap']) is int and value['expected_startup_cap'] in (8, 12),
            'Root must select explicit startup cap8 or12')
    validate_stopped(value, bridge)
    root = Path(value['output_directory'])
    require(root.is_absolute() and root.resolve(strict=False) == root and not root.exists(), 'Fresh held startup output required')
    output = Path(args.output)
    require(output.is_absolute() and output.resolve(strict=False) == output and output.parent.is_dir()
            and not output.exists() and output.parent != root, 'Fresh job in existing metadata directory required')
    job = dict(schema='robotron-continuous-main-before-update-startup-hold-job-v1', mode=MODE,
        original_attempt=1, no_retry=True, unit=value['unit'], original_selection=selected, operator_source=own,
        restoration_manifest=value['restoration_manifest'], stopped_CPU_report=value['stopped_CPU_report'],
        stopped_state_authority=value['stopped_state_authority'], checkpoint=value['checkpoint'],
        resume_record=value['resume_record'], source_pins=value['source_pins'], output_directory=str(root),
        release_path=str(root/'ROOT-release.json'), expected_startup_cap=value['expected_startup_cap'])
    result = bridge.publish(output, job)
    print(json.dumps(dict(status='PREPARED_STARTUP_JOB_NOT_LAUNCHED', job=result,
        required_environment=dict(ROBOTRON_CONTINUOUS_TRAINING_MODE='1', ROBOTRON_CONTINUOUS_STARTUP_HOLD='1',
            ROBOTRON_CONTINUOUS_STARTUP_JOB=result['path'], ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256=result['sha256'],
            DQN_PRIORITY_PHASE_RECORD=value['resume_record']['path'], DQN_PRIORITY_PHASE_RECORD_SHA256=value['resume_record']['sha256'],
            PYTHONUNBUFFERED='1', DQN_MAX_SAMPLES_PER_FRAME=str(value['expected_startup_cap'])), unset_environment=['ROBOTRON_TRAINING_ROUND_STATUS'],
        supervisor_not_started=True, Runtime_or_state_restoration_qualified=False)), flush=True)


def actual_owner(owner, job_pin, expected_startup_cap):
    require(set(owner) == {'pid','birth','unit','invocation_id','cgroup','uid'}
            and owner['unit'] == 'robotron-trainer.service' and owner['uid'] == os.getuid()
            and type(owner['pid']) is int and owner['pid'] > 1 and type(owner['birth']) is int,
            'Exact actual held trainer identity required')
    raw = subprocess.check_output(['systemctl','--user','show',owner['unit']], text=True, timeout=5)
    values = dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
    wanted = dict(Id=owner['unit'], MainPID=str(owner['pid']), Type='exec', ActiveState='active',
        SubState='running', Restart='no', NRestarts='0', InvocationID=owner['invocation_id'], ControlGroup=owner['cgroup'])
    require(all(values.get(k) == v for k,v in wanted.items()) and re.fullmatch('[0-9a-f]{32}',owner['invocation_id']),
            'Held unit no longer owns the exact original incarnation')
    proc = Path('/proc',str(owner['pid']))
    birth = int((proc/'stat').read_text().rsplit(')',1)[1].split()[19])
    require(birth == owner['birth'] and proc.stat().st_uid == owner['uid']
            and (proc/'cgroup').read_text().splitlines() == ['0::'+owner['cgroup']], 'Held process birth/cgroup/UID changed')
    require(type(expected_startup_cap) is int and expected_startup_cap in (8, 12), 'Explicit selected startup cap required')
    env_records = [x.split('=',1) for x in (proc/'environ').read_bytes().decode().split('\0') if '=' in x]
    require([v for k,v in env_records if k == 'DQN_MAX_SAMPLES_PER_FRAME'] == [str(expected_startup_cap)],
            'Actual held unit process startup cap differs or is duplicated')
    env = dict(env_records)
    wanted_env = dict(ROBOTRON_CONTINUOUS_TRAINING_MODE='1', ROBOTRON_CONTINUOUS_STARTUP_HOLD='1',
        ROBOTRON_CONTINUOUS_STARTUP_JOB=job_pin['path'], ROBOTRON_CONTINUOUS_STARTUP_JOB_SHA256=job_pin['sha256'], PYTHONUNBUFFERED='1',
        DQN_MAX_SAMPLES_PER_FRAME=str(expected_startup_cap))
    require(all(env.get(k) == v for k,v in wanted_env.items()) and not env.get('LD_PRELOAD')
            and not env.get('ROBOTRON_TRAINING_ROUND_STATUS'), 'Actual process hold environment differs')
    return dict(owner=owner, unit_fields={k: values[k] for k in wanted},
        expected_startup_cap=expected_startup_cap, process_startup_environment_cap=env['DQN_MAX_SAMPLES_PER_FRAME'])


def release(args):
    own = source(args); bridge = bridge_module()
    job_pin, job = selected_json(args.job, args.job_sha256, bridge)
    require(job['schema'] == 'robotron-continuous-main-before-update-startup-hold-job-v1'
            and job['mode'] == MODE and job['operator_source'] == own and job['original_attempt'] == 1
            and job['no_retry'] is True, 'Exact one-use prepared job required')
    held_pin, held = selected_json(args.held_report, args.held_report_sha256, bridge)
    root = Path(job['output_directory']); release_path = Path(job['release_path'])
    require(held_pin['path'] == str(root/'verified-held-before-first-update.json')
            and release_path == root/'ROOT-release.json' and stat.S_IMODE(root.stat().st_mode) == 0o700
            and root.stat().st_uid == os.getuid() and not root.is_symlink(), 'Exact private held output required')
    require(held['schema'] == 'robotron-continuous-main-held-exact-restoration-report-v1'
            and held['status'] == 'VERIFIED_HELD_BEFORE_FIRST_UPDATE' and held['original_job'] == job_pin
            and held['checkpoint'] == job['checkpoint'] and held['restoration_manifest'] == job['restoration_manifest']
            and held['stopped_CPU_report'] == job['stopped_CPU_report']
            and held['all_online_target_Adam_scaler_payloads_equal'] is True
            and held['optimizer_implementation_flags_exactly_equal'] is True
            and held['training_and_memory_locks_held_until_Root_release'] is True
            and held['dashboard_and_GAME_listener_not_created'] is True
            and held['optimizer_attempts_before_release'] == held['new_replay_inserts_before_release'] == 0,
            'Actual held restoration report is not release-ready')
    require(type(job['expected_startup_cap']) is int and job['expected_startup_cap'] in (8, 12)
            and held['startup_budget']['expected_startup_cap'] == job['expected_startup_cap']
            and held['startup_budget']['runtime_cap'] == job['expected_startup_cap']
            and held['startup_budget']['process_startup_environment_cap'] == str(job['expected_startup_cap'])
            and held['startup_budget']['fresh_per_boot_baseline_verified'] is True
            and held['startup_budget']['anchor_installed_or_rebased'] is False,
            'Held report does not prove the exact selected startup cap and existing fresh budget')
    require(not release_path.exists() and not (root/'release-consumed.json').exists(), 'Release is one-use; no retry/overwrite')
    validate_stopped(job, bridge)
    before = actual_owner(held['owner'], job_pin, job['expected_startup_cap'])
    value = dict(schema='robotron-root-continuous-startup-one-use-release-v1', owner=held['owner'],
        original_job=job_pin, held_report=held_pin, checkpoint=job['checkpoint'], allow_training=True,
        operator_source=own, original_attempt=1, no_retry=True,
        expected_startup_cap=job['expected_startup_cap'], startup_budget=held['startup_budget'])
    stage = root/('.ROOT-release-staged-'+str(os.getpid())+'.json')
    bridge.publish(stage, value)
    require(actual_owner(held['owner'], job_pin, job['expected_startup_cap']) == before, 'Held owner changed before publication')
    os.link(stage, release_path, follow_symlinks=False)  # Exclusive; existing release never replaced.
    stage.unlink()
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
    release_pin = full_pin(release_path)
    bridge.read(release_pin)
    print(json.dumps(dict(status='ONE_USE_ROOT_RELEASE_PUBLISHED', Root_release=release_pin,
        held_report=held_pin, training_may_now_begin=True, actual_learning_or_static192_qualified=False)), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    modes = p.add_mutually_exclusive_group(); modes.add_argument('--prepare-job',action='store_true'); modes.add_argument('--release',action='store_true')
    p.add_argument('--expected-source-sha256'); p.add_argument('--selection'); p.add_argument('--selection-sha256'); p.add_argument('--output')
    p.add_argument('--job'); p.add_argument('--job-sha256'); p.add_argument('--held-report'); p.add_argument('--held-report-sha256')
    args = p.parse_args()
    if args.prepare_job: prepare_job(args)
    elif args.release: release(args)
    else: print('PLAN_ONLY_NO_READS_OR_ACTIONS')


if __name__ == '__main__':
    main()
